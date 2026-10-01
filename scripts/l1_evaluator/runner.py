"""Runner — executes project tests in Docker using the unified image."""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

_DOCKER_DIR = str(Path(__file__).resolve().parents[2] / "docker")
if _DOCKER_DIR not in sys.path:
    sys.path.insert(0, _DOCKER_DIR)

from runner_lib import build_script, docker_command  # noqa: E402

from .workspace import Workspace  # noqa: E402

_CHMOD_FIX = (
    "find /workspace/src/node_modules/.bin -type f -o -type l 2>/dev/null"
    " | xargs chmod +x 2>/dev/null || true"
)


def _fix_js_permissions(install_command: str) -> str:
    STRIP_PREPARE = (
        "python3 -c \""
        "import json,sys; "
        "p=open('package.json'); d=json.load(p); p.close(); "
        "d.get('scripts',{}).pop('prepare',None); "
        "open('package.json','w').write(json.dumps(d,indent=2))"
        "\" 2>/dev/null || true"
        " && rm -f package-lock.json"
    )

    FIX_TSC = (
        "find . -maxdepth 2 -name '*.js' -not -path './node_modules/*' 2>/dev/null"
        " | xargs grep -l 'node_modules/.bin/tsc' 2>/dev/null"
        " | xargs sed -i"
        r" 's|\\./node_modules/\\.bin/tsc|node node_modules/typescript/bin/tsc|g'"
        " 2>/dev/null || true"
    )

    def _replacer(m: re.Match) -> str:
        return STRIP_PREPARE + " && " + m.group(0) + " && " + _CHMOD_FIX + " && " + FIX_TSC

    patched = re.sub(
        r"npm install(?:\s+[^\&\|;]+?)?(?=\s*&&|\s*;|\s*\|\||\s*$)",
        _replacer,
        install_command,
        count=1,
    )
    return patched if patched != install_command else (
        install_command.rstrip() + " && " + _CHMOD_FIX
    )


def run(
    workspace: Workspace,
    task_dir: Path,
    install_command: str,
    test_command: str,
    *,
    timeout: int = 300,
) -> dict:
    language = task_dir.parents[2].name
    docker_image = workspace.run_config.get("docker_image", "")

    effective_install = install_command
    if language == "javascript" and install_command.strip():
        effective_install = _fix_js_permissions(install_command)

    script = build_script(effective_install, test_command)
    cmd = docker_command(workspace.tmp_dir, script, language=language, docker_image=docker_image)

    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired:
        exit_code = -1
        stdout = ""
        stderr = f"Docker run timed out after {timeout}s"

    return {
        "passed": exit_code == 0,
        "exit_code": exit_code,
        "duration_seconds": round(time.monotonic() - start, 2),
        "stdout": stdout[-32000:],
        "stderr": stderr[-8000:],
    }
