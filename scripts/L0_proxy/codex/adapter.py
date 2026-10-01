"""Codex adapter for L0 project-from-scratch generation."""

from __future__ import annotations

import json
import os
import random
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[3]
_WORKSPACE_ROOT = Path("/tmp/pce_codex_l0_workspaces")
_CONTAINER_NAME = "cceval-codex-l0-worker"
_IMAGE_NAME = "cceval-codex-l0:latest"
_DEFAULT_MODEL = "gpt-5.4"
_IMAGE_SENTINEL = "cceval-codex-l0:latest.dockerfile-sha256"
_RETRYABLE_PATTERNS = (
    "429 too many requests",
    "rate limit",
    "exceeded retry limit",
    "temporarily unavailable",
    "service unavailable",
    "connection reset",
    "timed out",
    "timeout",
)

sys.path.insert(0, str(_REPO_ROOT / "scripts"))


class CodexL0Error(RuntimeError):
    pass


_CODEX_MD = """\
You are a code generation assistant.
- Your task (a PRD) is described in prompt.md at the workspace root.
- Create ALL source files inside the src/ directory.
- Include build/config files (build.gradle, package.json, pom.xml, Makefile, etc.) as needed.
- A reference/ directory may be present with the oracle project's original build configuration.
  Use it as a reference for exact dependency versions, package names, and project structure.
  Do NOT copy it verbatim; generate your own files in src/.
- Do NOT ask questions or provide explanations.
- When done, stop immediately.
"""

_REFERENCE_FILES = [
    "requirements.txt", "setup.py", "setup.cfg", "pyproject.toml",
    "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
    "pom.xml",
    "go.mod", "go.sum",
    "CMakeLists.txt", "Makefile", "meson.build",
    "package.json", "tsconfig.json", "tsconfig.build.json",
]
_REFERENCE_DIRS = ["gradle", ".mvn"]


def _load_dotenv() -> dict[str, str]:
    env_file = _REPO_ROOT / ".env"
    dotenv: dict[str, str] = {}
    if not env_file.is_file():
        return dotenv
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        dotenv[key.strip()] = value.strip()
    return dotenv


def _build_codex_config(model: str, base_url: str | None) -> str:
    lines = [f'model = "{model}"', 'disable_response_storage = true']

    if base_url:
        lines.extend([
            'model_provider = "proxy"',
            "",
            "[model_providers.proxy]",
            'name = "OpenAI-compatible proxy"',
            f'base_url = "{base_url}"',
            'env_key = "OPENAI_API_KEY"',
            'wire_api = "responses"',
            'request_max_retries = 6',
            'stream_max_retries = 8',
            'supports_websockets = false',
        ])

    return "\n".join(lines) + "\n"


def _dockerfile_hash() -> str:
    import hashlib
    dockerfile = _THIS_FILE.parent / "Dockerfile"
    return hashlib.sha256(dockerfile.read_bytes()).hexdigest()


def _ensure_container() -> None:
    check = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name={_CONTAINER_NAME}"],
        capture_output=True, text=True,
    )
    if check.stdout.strip():
        return

    stopped = subprocess.run(
        ["docker", "ps", "-aq", "-f", f"name={_CONTAINER_NAME}"],
        capture_output=True, text=True,
    ).stdout.strip()
    if stopped:
        subprocess.run(["docker", "rm", "-f", _CONTAINER_NAME], capture_output=True, text=True)

    dockerfile_hash = _dockerfile_hash()
    sentinel = _WORKSPACE_ROOT / _IMAGE_SENTINEL
    cached_hash = sentinel.read_text(encoding="utf-8").strip() if sentinel.is_file() else ""

    has_image = subprocess.run(
        ["docker", "images", "-q", _IMAGE_NAME],
        capture_output=True, text=True,
    ).stdout.strip()

    if not has_image or cached_hash != dockerfile_hash:
        dockerfile = _THIS_FILE.parent / "Dockerfile"
        print(f"Building Docker image {_IMAGE_NAME}...")
        ret = subprocess.run([
            "docker", "build", "-t", _IMAGE_NAME,
            "-f", str(dockerfile), str(_THIS_FILE.parent),
        ])
        if ret.returncode != 0:
            raise CodexL0Error("Docker image build failed")
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text(dockerfile_hash, encoding="utf-8")

    _WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

    dotenv = _load_dotenv()
    env_args: list[str] = []

    openai_key = (
        dotenv.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    if openai_key:
        env_args += ["-e", f"OPENAI_API_KEY={openai_key}"]

    openai_base = (
        os.environ.get("OPENAI_BASE_URL")
        or dotenv.get("OPENAI_BASE_URL")
    )
    if openai_base:
        env_args += ["-e", f"OPENAI_BASE_URL={openai_base}"]

    ret = subprocess.run([
        "docker", "run", "-d",
        "--name", _CONTAINER_NAME,
        "-v", f"{_WORKSPACE_ROOT}:/workspaces",
        *env_args,
        _IMAGE_NAME,
    ], capture_output=True, text=True)

    if ret.returncode != 0:
        raise CodexL0Error(f"Container start failed: {ret.stderr}")

    codex_home = _WORKSPACE_ROOT / "codex_home"
    codex_home.mkdir(parents=True, exist_ok=True)
    (codex_home / "config.toml").write_text("", encoding="utf-8")

    print(f"Container started: {_CONTAINER_NAME}")
    print(f"Stop: docker stop {_CONTAINER_NAME} && docker rm {_CONTAINER_NAME}\n")


def _run_codex_in_container(
    workspace_name: str,
    prompt: str,
    model: str,
    *,
    timeout: int = 1200,
) -> dict:
    _ensure_container()
    dotenv = _load_dotenv()
    openai_base = os.environ.get("OPENAI_BASE_URL") or dotenv.get("OPENAI_BASE_URL")
    codex_config = _build_codex_config(model, openai_base)
    codex_home = _WORKSPACE_ROOT / "codex_home"
    codex_home.mkdir(parents=True, exist_ok=True)
    (codex_home / "config.toml").write_text(codex_config, encoding="utf-8")

    cmd = [
        "docker", "exec",
        "-e", "CODEX_HOME=/workspaces/codex_home",
        _CONTAINER_NAME,
        "codex", "exec",
        "--cd", f"/workspaces/{workspace_name}",
        prompt,
        "--model", model,
        "--ephemeral",
        "--dangerously-bypass-approvals-and-sandbox",
        "--skip-git-repo-check",
        "--color", "never",
        "--json",
    ]

    attempts = 4
    base_delay_s = 8.0
    last_error = ""

    for attempt in range(1, attempts + 1):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as e:
            last_error = f"Codex timed out after {timeout}s"
            if attempt == attempts:
                raise CodexL0Error(last_error) from e
        else:
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            combined = f"{stdout}\n{stderr}".lower()

            if result.returncode == 0:
                events = []
                for line in stdout.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

                if not events:
                    raise CodexL0Error(f"Codex returned no JSON events.\nstdout: {stdout[:500]}")

                final_event = events[-1]
                return {
                    "events": events,
                    "final_event": final_event,
                    "stdout": stdout,
                    "stderr": stderr,
                }

            error_lines = stderr.splitlines()[-40:]
            for line in stdout.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "error":
                    error_lines.append(str(event.get("message", "")))
                turn_failed = event.get("type") == "turn.failed"
                if turn_failed:
                    error_lines.append(str(event.get("error", {}).get("message", "")))
            last_error = f"Codex failed (exit {result.returncode}):\n" + "\n".join(line for line in error_lines if line)
            retryable = any(pattern in combined for pattern in _RETRYABLE_PATTERNS)
            if not retryable or attempt == attempts:
                raise CodexL0Error(last_error)

        sleep_s = base_delay_s * (2 ** (attempt - 1)) + random.uniform(0, 2.0)
        print(f"Codex retry {attempt}/{attempts} after {sleep_s:.1f}s: {last_error[:120]}")
        time.sleep(sleep_s)

    raise CodexL0Error(last_error or "Codex failed")


def _extract_usage(result_json: dict, model: str) -> dict:
    events = result_json.get("events", [])

    total_input = 0
    total_output = 0
    total_reasoning = 0
    cached_input = 0
    turns = 0

    for event in events:
        if event.get("type") != "turn.completed":
            continue
        usage = event.get("usage", {})
        total_input += int(usage.get("input_tokens", 0) or 0)
        total_output += int(usage.get("output_tokens", 0) or 0)
        total_reasoning += int(usage.get("reasoning_output_tokens", 0) or 0)
        cached_input += int(usage.get("cached_input_tokens", 0) or 0)
        turns += 1

    return {
        "input_tokens": total_input,
        "output_tokens": total_output,
        "reasoning_output_tokens": total_reasoning,
        "cache_read_input_tokens": cached_input,
        "cache_creation_input_tokens": 0,
        "total_tokens": total_input + total_output,
        "cost_usd": 0,
        "model": model,
        "num_turns": turns,
    }


def _prepare_workspace(task_dir: Path) -> tuple[Path, str]:
    from l0_evaluator.workspace import Workspace

    ws = Workspace(task_dir)
    ws.build()

    workspace_name = ws.tmp_dir.name
    mount_path = _WORKSPACE_ROOT / workspace_name

    if mount_path.exists():
        shutil.rmtree(mount_path)
    shutil.copytree(ws.tmp_dir, mount_path)

    (mount_path / "CODEX.md").write_text(_CODEX_MD, encoding="utf-8")
    prompt_src = task_dir / "prompt.md"
    if prompt_src.exists():
        shutil.copy(prompt_src, mount_path / "prompt.md")

    project_dir = task_dir.parents[1]
    oracle_src = project_dir / "src"
    if oracle_src.is_dir():
        ref_dir = mount_path / "reference"
        for name in _REFERENCE_FILES:
            src_path = oracle_src / name
            if src_path.is_file():
                ref_dir.mkdir(exist_ok=True)
                shutil.copy2(src_path, ref_dir / name)
        for name in _REFERENCE_DIRS:
            src_path = oracle_src / name
            if src_path.is_dir():
                ref_dir.mkdir(exist_ok=True)
                shutil.copytree(src_path, ref_dir / name)

    run_config_src = task_dir / "run_config.json"
    if run_config_src.exists():
        run_config = json.loads(run_config_src.read_text(encoding="utf-8"))
        hint = (
            "\n\n---\n"
            f"Test environment: docker image `{run_config.get('docker_image', 'unknown')}`\n"
            f"Test command: `{run_config.get('test_command', 'unknown')}`\n"
        )
        prompt_file = mount_path / "prompt.md"
        if prompt_file.exists():
            prompt_file.write_text(
                prompt_file.read_text(encoding="utf-8") + hint,
                encoding="utf-8",
            )

    ws.cleanup()
    return mount_path, workspace_name


def generate_project(task_dir: Path, model: str, output_dir: Path) -> tuple[dict[str, str], dict]:
    """Generate a complete project for an L0 task. Returns (file_map, usage_dict)."""
    task_json = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    lang = task_json.get("stub_info", {}).get("lang", "")

    mount_path, workspace_name = _prepare_workspace(task_dir)

    cli_prompt = (
        "你的任务是：根据 prompt.md 中的 PRD（产品需求文档），从零生成一个完整的可运行项目。\n\n"
        "请：\n"
        "1. 读取 prompt.md 理解需求\n"
        f"2. 在 src/ 目录下创建完整的 {lang} 项目代码（包含配置文件、源代码等）\n"
        "3. 如存在 reference/，可参考其构建配置、依赖版本和项目结构，但不要直接拷贝\n"
        "4. 确保项目结构完整，能通过自动化测试\n"
        "5. 完成后立即停止\n"
    )

    start_time = time.time()
    result_json = _run_codex_in_container(workspace_name, cli_prompt, model)
    duration = time.time() - start_time

    file_map: dict[str, str] = {}
    src_dir = mount_path / "src"
    if src_dir.exists():
        for path in sorted(src_dir.rglob("*")):
            if path.is_file():
                try:
                    rel_path = str(path.relative_to(src_dir))
                    file_map[rel_path] = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    pass

    usage = _extract_usage(result_json, model)
    usage["duration_s"] = round(duration, 1)
    usage["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    debug_dir = (
        output_dir / "debug" / task_dir.parents[2].name /
        task_dir.parents[1].name / task_dir.name
    )
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "usage.json").write_text(
        json.dumps(usage, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (debug_dir / "codex_response.json").write_text(
        json.dumps(result_json, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    shutil.rmtree(mount_path, ignore_errors=True)
    return file_map, usage
