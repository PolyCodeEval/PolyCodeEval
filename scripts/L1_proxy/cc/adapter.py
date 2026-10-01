"""Claude Code adapter for L1 project-level generation."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[3]
_WORKSPACE_ROOT = Path("/tmp/pce_cc_l1_workspaces")
_CONTAINER_NAME = "cceval-l1-worker"
_IMAGE_NAME = "cceval-l1:latest"
_DEFAULT_MODEL = "claude-sonnet-4-6"

sys.path.insert(0, str(_REPO_ROOT / "scripts"))


class CCL1Error(RuntimeError):
    pass


_CLAUDE_MD = """\
You are a code generation assistant.
- Your task (a PRD) is described in prompt.md at the workspace root.
- Create ALL source files inside the src/ directory.
- The src/ directory may already contain a project skeleton from hollowed_files/.
  Use it as a starting point, but complete the full project so it is runnable.
- Keep the repository layout under src/ clean and canonical.
- If a skeleton file already exists in src/, edit that file in place instead of creating a duplicate copy elsewhere.
- Do NOT create parallel copies of the same module/package/file under another path just to avoid editing the provided skeleton.
- If you determine that a provided skeleton file belongs at a different canonical path, move/merge it into the correct location and do NOT leave a stale duplicate behind.
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

    has_image = subprocess.run(
        ["docker", "images", "-q", _IMAGE_NAME],
        capture_output=True, text=True,
    ).stdout.strip()

    if not has_image:
        dockerfile = _THIS_FILE.parent / "Dockerfile"
        print(f"Building Docker image {_IMAGE_NAME}...")
        ret = subprocess.run([
            "docker", "build", "-t", _IMAGE_NAME,
            "-f", str(dockerfile), str(_THIS_FILE.parent),
        ])
        if ret.returncode != 0:
            raise CCL1Error("Docker image build failed")

    _WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

    env_args: list[str] = []

    dotenv = _load_dotenv()
    anthropic_key = (
        dotenv.get("ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    )
    if anthropic_key:
        env_args += ["-e", f"ANTHROPIC_API_KEY={anthropic_key}"]

    anthropic_base = os.environ.get("ANTHROPIC_BASE_URL")
    if not anthropic_base:
        openai_base = dotenv.get("OPENAI_BASE_URL", "")
        if openai_base:
            anthropic_base = openai_base.rstrip("/").removesuffix("/v1")
    if anthropic_base:
        env_args += ["-e", f"ANTHROPIC_BASE_URL={anthropic_base}"]

    ret = subprocess.run([
        "docker", "run", "-d",
        "--name", _CONTAINER_NAME,
        "-v", f"{_WORKSPACE_ROOT}:/workspaces",
        *env_args,
        _IMAGE_NAME,
    ], capture_output=True, text=True)

    if ret.returncode != 0:
        raise CCL1Error(f"Container start failed: {ret.stderr}")

    print(f"Container started: {_CONTAINER_NAME}")
    print(f"Stop: docker stop {_CONTAINER_NAME} && docker rm {_CONTAINER_NAME}\n")


def _run_claude_in_container(workspace_name: str, prompt: str, model: str,
                             max_turns: int = 100, timeout: int = 1800) -> dict:
    _ensure_container()

    prompt_escaped = shlex.quote(prompt)
    cmd = [
        "docker", "exec", _CONTAINER_NAME,
        "bash", "-c",
        f"cd /workspaces/{workspace_name} && "
        f"claude -p {prompt_escaped} "
        f"--model {model} "
        f"--permission-mode bypassPermissions "
        f"--output-format json "
        f"--max-turns {max_turns}",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise CCL1Error(f"Claude timed out after {timeout}s") from e

    if result.returncode != 0:
        stderr_tail = "\n".join(result.stderr.splitlines()[-40:])
        raise CCL1Error(f"Claude failed (exit {result.returncode}):\n{stderr_tail}")

    stdout = result.stdout.strip()
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as e:
        raise CCL1Error(f"JSON parse error: {e}\nstdout: {stdout[:500]}")


def _extract_usage(result_json: dict, model: str) -> dict:
    usage_raw = result_json.get("usage", {})
    model_usage = result_json.get("modelUsage", {})

    if model_usage:
        model_data = model_usage.get(model, next(iter(model_usage.values()), {}))
        input_tokens = model_data.get("inputTokens", 0)
        output_tokens = model_data.get("outputTokens", 0)
        cache_read = model_data.get("cacheReadInputTokens", 0)
        cache_creation = model_data.get("cacheCreationInputTokens", 0)
        cost_usd = model_data.get("costUSD", 0)
    else:
        input_tokens = usage_raw.get("input_tokens", 0)
        output_tokens = usage_raw.get("output_tokens", 0)
        cache_read = usage_raw.get("cache_read_input_tokens", 0)
        cache_creation = usage_raw.get("cache_creation_input_tokens", 0)
        cost_usd = result_json.get("total_cost_usd", 0)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_creation,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": cost_usd,
        "model": model,
        "num_turns": result_json.get("num_turns", 0),
    }


def _prepare_workspace(task_dir: Path) -> tuple[Path, str]:
    from l1_evaluator.workspace import Workspace

    ws = Workspace(task_dir)
    ws.build()

    workspace_name = ws.tmp_dir.name
    mount_path = _WORKSPACE_ROOT / workspace_name

    if mount_path.exists():
        shutil.rmtree(mount_path)
    shutil.copytree(ws.tmp_dir, mount_path)

    hollowed_dir = task_dir / "hollowed_files"
    if hollowed_dir.is_dir():
        for src_path in sorted(hollowed_dir.rglob("*")):
            if not src_path.is_file():
                continue
            rel_path = src_path.relative_to(hollowed_dir)
            dest_path = mount_path / "src" / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dest_path)

    (mount_path / "CLAUDE.md").write_text(_CLAUDE_MD, encoding="utf-8")
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
            f"\n\n---\n"
            f"Test environment: docker image `{run_config.get('docker_image', 'unknown')}`\n"
            f"Test command: `{run_config.get('test_command', 'unknown')}`\n"
        )
        prompt_file = mount_path / "prompt.md"
        if prompt_file.exists():
            prompt_file.write_text(
                prompt_file.read_text(encoding="utf-8") + hint, encoding="utf-8")

    ws.cleanup()
    return mount_path, workspace_name


def generate_files(task_dir: Path, model: str, output_dir: Path) -> tuple[dict[str, str], dict]:
    """Generate a full project tree for an L1 task. Returns (file_map, usage_dict)."""
    mount_path, workspace_name = _prepare_workspace(task_dir)
    task_json = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    lang = task_json.get("stub_info", {}).get("lang", "") or task_dir.parents[2].name

    cli_prompt = (
        "你的任务是：根据 prompt.md 中的内容，生成一个完整的可运行项目。\n\n"
        "请：\n"
        "1. 读取 prompt.md 理解需求\n"
        f"2. 在 src/ 目录下完成整个 {lang} 项目代码（包含配置文件、源代码等）\n"
        "3. 如果 src/ 中已提供项目骨架，请直接在这些现有文件上填充和修改，不要复制出另一份平行实现\n"
        "4. 如果判断骨架文件当前路径不合理，可以移动到正确的规范位置，但移动后原位置不要保留重复文件或重复实现\n"
        "5. 保持 src/ 下仓库结构整洁，不要新增重复模块、重复包名或仅用于绕过骨架的备份文件\n"
        "6. 如存在 reference/，可参考其构建配置、依赖版本和项目结构，但不要直接拷贝\n"
        "7. 确保项目结构完整，能通过自动化测试\n"
        "8. 完成后立即停止\n"
    )

    start_time = time.time()
    result_json = _run_claude_in_container(workspace_name, cli_prompt, model)
    duration = time.time() - start_time

    file_map: dict[str, str] = {}
    src_dir = mount_path / "src"
    for file_path in sorted(src_dir.rglob("*")):
        if not file_path.is_file():
            continue
        rel_path = str(file_path.relative_to(src_dir))
        try:
            file_map[rel_path] = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

    usage = _extract_usage(result_json, model)
    usage["duration_s"] = round(duration, 1)
    usage["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    debug_dir = (output_dir / "debug" / task_dir.parents[2].name /
                 task_dir.parents[1].name / task_dir.name)
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "usage.json").write_text(
        json.dumps(usage, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (debug_dir / "claude_response.json").write_text(
        json.dumps(result_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    shutil.rmtree(mount_path, ignore_errors=True)
    return file_map, usage
