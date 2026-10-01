"""Claude Code adapter for L0 project-from-scratch generation."""

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
_WORKSPACE_ROOT = Path("/tmp/pce_cc_l0_workspaces")
_CONTAINER_NAME = "cceval-l0-worker"
_IMAGE_NAME = "cceval-l0:latest"
_DEFAULT_MODEL = "claude-sonnet-4-6"

sys.path.insert(0, str(_REPO_ROOT / "scripts"))


class CCL0Error(RuntimeError):
    pass


_CLAUDE_MD = """\
You are a code generation assistant.
- Your task (a PRD) is described in prompt.md at the workspace root.
- Use the Write tool to create ALL source files inside the src/ directory.
- Include build/config files (build.gradle, package.json, pom.xml, Makefile, etc.) as needed.
- You MUST use file creation tools (Write/Edit) — do NOT output file contents as text.
- A reference/ directory may be present with the oracle project's original build configuration.
  Use it as a reference for exact dependency versions, package names, and project structure.
  Do NOT copy it verbatim; generate your own files in src/.
- Do NOT ask questions or provide explanations.
- When done, stop immediately.
"""

# Reference config files to copy from oracle src/ into workspace reference/
_REFERENCE_FILES = [
    # Python
    "requirements.txt", "setup.py", "setup.cfg", "pyproject.toml",
    # Java (Gradle)
    "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
    # Java (Maven)
    "pom.xml",
    # Go
    "go.mod", "go.sum",
    # C++
    "CMakeLists.txt", "Makefile", "meson.build",
    # JavaScript/TypeScript
    "package.json", "tsconfig.json", "tsconfig.build.json",
]
# Directory-type reference items (copied recursively)
_REFERENCE_DIRS = ["gradle", ".mvn"]


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
            raise CCL0Error("Docker image build failed")

    _WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

    env_args: list[str] = []

    # Load .env from repo root to get project-level API keys
    _env_file = _REPO_ROOT / ".env"
    _dotenv: dict[str, str] = {}
    if _env_file.is_file():
        for _line in _env_file.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _, _v = _line.partition("=")
            _dotenv[_k.strip()] = _v.strip()

    # Prefer .env ANTHROPIC_API_KEY over shell ANTHROPIC_AUTH_TOKEN
    anthropic_key = (
        _dotenv.get("ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    )
    if anthropic_key:
        env_args += ["-e", f"ANTHROPIC_API_KEY={anthropic_key}"]

    # Base URL: shell env takes precedence, then derive from OPENAI_BASE_URL in .env
    anthropic_base = os.environ.get("ANTHROPIC_BASE_URL")
    if not anthropic_base:
        openai_base = _dotenv.get("OPENAI_BASE_URL", "")
        if openai_base:
            # yunwu.ai/v1 -> yunwu.ai (Anthropic endpoint without /v1)
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
        raise CCL0Error(f"Container start failed: {ret.stderr}")

    print(f"Container started: {_CONTAINER_NAME}")
    print(f"Stop: docker stop {_CONTAINER_NAME} && docker rm {_CONTAINER_NAME}\n")


def _run_claude_in_container(workspace_name: str, prompt: str, model: str,
                             max_turns: int = 80, timeout: int = 1200) -> dict:
    _ensure_container()

    prompt_escaped = shlex.quote(prompt)
    cmd = [
        "docker", "exec", "-i", _CONTAINER_NAME,
        "bash", "-c",
        f"cd /workspaces/{workspace_name} && "
        f"claude -p {prompt_escaped} "
        f"--model {model} "
        f"--permission-mode bypassPermissions "
        f"--output-format json "
        f"--max-turns {max_turns}",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    if result.returncode != 0:
        stderr_tail = "\n".join(result.stderr.splitlines()[-40:])
        raise CCL0Error(f"Claude failed (exit {result.returncode}):\n{stderr_tail}")

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
        raise CCL0Error(f"JSON parse error: {e}\nstdout: {stdout[:500]}")


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
    from l0_evaluator.workspace import Workspace

    ws = Workspace(task_dir)
    ws.build()

    workspace_name = ws.tmp_dir.name
    mount_path = _WORKSPACE_ROOT / workspace_name

    if mount_path.exists():
        shutil.rmtree(mount_path)
    shutil.copytree(ws.tmp_dir, mount_path)

    (mount_path / "CLAUDE.md").write_text(_CLAUDE_MD, encoding="utf-8")
    prompt_src = task_dir / "prompt.md"
    if prompt_src.exists():
        shutil.copy(prompt_src, mount_path / "prompt.md")

    # Inject oracle build config files into reference/ so claude can see exact
    # dependency versions, package names, and project structure.
    project_dir = task_dir.parents[1]
    oracle_src = project_dir / "src"
    if oracle_src.is_dir():
        ref_dir = mount_path / "reference"
        copied_any = False
        for name in _REFERENCE_FILES:
            src_path = oracle_src / name
            if src_path.is_file():
                ref_dir.mkdir(exist_ok=True)
                shutil.copy2(src_path, ref_dir / name)
                copied_any = True
        for name in _REFERENCE_DIRS:
            src_path = oracle_src / name
            if src_path.is_dir():
                ref_dir.mkdir(exist_ok=True)
                shutil.copytree(src_path, ref_dir / name)
                copied_any = True

    # Append test command hint to prompt so claude knows how the project will be run
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


def _parse_file_format(text: str) -> dict[str, str]:
    """Parse ===FILE: path=== delimited output as fallback when tools weren't used."""
    import re
    result: dict[str, str] = {}
    pattern = re.compile(r"===FILE:\s*(.+?)===\n(.*?)(?=\n===FILE:|\Z)", re.DOTALL)
    for m in pattern.finditer(text):
        rel_path = m.group(1).strip()
        content = m.group(2).rstrip("\n")
        # Strip leading "src/" if present in path
        if rel_path.startswith("src/"):
            rel_path = rel_path[4:]
        result[rel_path] = content
    return result


def generate_project(task_dir: Path, model: str, output_dir: Path) -> tuple[dict[str, str], dict]:
    """Generate a complete project for an L0 task. Returns (file_map, usage_dict)."""
    task_json = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    lang = task_json.get("stub_info", {}).get("lang", "")

    mount_path, workspace_name = _prepare_workspace(task_dir)

    cli_prompt = (
        "你的任务是：根据 prompt.md 中的内容，从零生成一个完整的可运行项目。\n\n"
        "请：\n"
        "1. 读取 prompt.md 理解需求\n"
        f"2. 在 src/ 目录下创建完整的 {lang} 项目代码（包含配置文件、源代码等）\n"
        "3. 确保项目结构完整，能通过自动化测试\n"
        "4. 完成后立即停止\n"
    )

    start_time = time.time()
    result_json = _run_claude_in_container(workspace_name, cli_prompt, model)
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

    # Fallback: parse ===FILE:=== format from result text if no files were written
    if not file_map:
        result_text = result_json.get("result", "")
        if result_text:
            parsed = _parse_file_format(result_text)
            if parsed:
                file_map = parsed
                # Write parsed files to disk so precomputed solver can read them
                for rel_path, content in parsed.items():
                    target = mount_path / "src" / rel_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content, encoding="utf-8")

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
