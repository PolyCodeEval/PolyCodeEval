"""Claude Code adapter for L2 file-level generation."""

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
_WORKSPACE_ROOT = Path("/tmp/pce_cc_l2_workspaces")
_CONTAINER_NAME = "cceval-l2-worker"
_IMAGE_NAME = "cceval-l2:latest"
_DEFAULT_MODEL = "claude-sonnet-4-6"

sys.path.insert(0, str(_REPO_ROOT / "scripts"))


class CCL2Error(RuntimeError):
    pass


_CLAUDE_MD = """\
You are a code completion assistant working in a repository.
- Your task is described in prompt.md at the workspace root.
- Edit the specified source files directly using your tools.
- Do NOT ask questions or provide explanations.
- When done, stop immediately.
"""


def _ensure_container() -> None:
    check = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name={_CONTAINER_NAME}"],
        capture_output=True, text=True,
    )
    if check.stdout.strip():
        return

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
            raise CCL2Error("Docker image build failed")

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

    anthropic_key = (
        _dotenv.get("ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    )
    if anthropic_key:
        env_args += ["-e", f"ANTHROPIC_API_KEY={anthropic_key}"]

    anthropic_base = os.environ.get("ANTHROPIC_BASE_URL")
    if not anthropic_base:
        openai_base = _dotenv.get("OPENAI_BASE_URL", "")
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
        raise CCL2Error(f"Container start failed: {ret.stderr}")

    print(f"Container started: {_CONTAINER_NAME}")
    print(f"Stop: docker stop {_CONTAINER_NAME} && docker rm {_CONTAINER_NAME}\n")


def _run_claude_in_container(workspace_name: str, prompt: str, model: str,
                             max_turns: int = 30, timeout: int = 600) -> dict:
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

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    if result.returncode != 0:
        stderr_tail = "\n".join(result.stderr.splitlines()[-40:])
        raise CCL2Error(f"Claude failed (exit {result.returncode}):\n{stderr_tail}")

    # claude --output-format json may emit non-JSON lines before the final JSON
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
        raise CCL2Error(f"JSON parse error: {e}\nstdout: {stdout[:500]}")


def _extract_usage(result_json: dict, model: str) -> dict:
    """Extract token usage from claude --output-format json response."""
    usage_raw = result_json.get("usage", {})
    model_usage = result_json.get("modelUsage", {})

    # Try modelUsage first (per-model breakdown), then fall back to top-level usage
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
    """Stage a runnable L2 workspace under the shared container mount."""
    from l2_evaluator.workspace import Workspace

    ws = Workspace(task_dir)
    workspace_name = f"pce_l2_{int(time.time() * 1000)}_{task_dir.name}"
    mount_path = _WORKSPACE_ROOT / workspace_name

    if mount_path.exists():
        shutil.rmtree(mount_path)
    mount_path.mkdir(parents=True, exist_ok=True)

    src_dst = mount_path / "src"
    shutil.copytree(ws.src_dir, src_dst)

    hollowed_root = task_dir / "hollowed_files"
    if hollowed_root.is_dir():
        for hollowed_file in hollowed_root.rglob("*"):
            if not hollowed_file.is_file():
                continue
            rel = hollowed_file.relative_to(hollowed_root)
            dst = src_dst / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(hollowed_file, dst)

    (mount_path / "CLAUDE.md").write_text(_CLAUDE_MD, encoding="utf-8")
    prompt_src = task_dir / "prompt.md"
    if prompt_src.exists():
        shutil.copy(prompt_src, mount_path / "prompt.md")

    ws.cleanup()
    return mount_path, workspace_name


def generate_file(task_dir: Path, model: str, output_dir: Path,
                  *, max_turns: int = 30, timeout: int = 600) -> tuple[str, dict]:
    """Generate a single file for an L2 task. Returns (file_content, usage_dict)."""
    task_json = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    target_file = task_json["stub_info"]["file"]

    mount_path, workspace_name = _prepare_workspace(task_dir)

    cli_prompt = (
        f"你的任务是：根据 prompt.md 中的描述，补全 src/{target_file} 文件中的所有 stub 函数。\n\n"
        "请：\n"
        "1. 读取 prompt.md 理解任务\n"
        f"2. 直接编辑 src/{target_file} 完成实现\n"
        "3. 完成后立即停止，不要输出任何解释\n"
    )

    start_time = time.time()
    result_json = _run_claude_in_container(
        workspace_name, cli_prompt, model, max_turns=max_turns, timeout=timeout
    )
    duration = time.time() - start_time

    from l2_evaluator.workspace import _resolve_file
    resolved = _resolve_file(mount_path / "src", target_file)
    result_file = mount_path / "src" / resolved
    file_content = result_file.read_text(encoding="utf-8") if result_file.exists() else ""

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
    return file_content, usage
