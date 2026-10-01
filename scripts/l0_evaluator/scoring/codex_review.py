"""Codex-driven review runner for L0 scoring dimensions.

This module prepares a Docker workspace containing:
- the generated repository snapshot under `repo/`
- the task prompt at `prompt.md`
- a mode-specific analysis prompt at `analysis_prompt.md`
- helper JSON/text artifacts used by the review prompt

It then runs `codex exec` non-interactively and parses the structured JSON
final message from the agent.
"""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import time
import uuid
from pathlib import Path

_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[3]
_WORKSPACE_ROOT = Path("/tmp/pce_codex_l0_review_workspaces")
_CONTAINER_NAME = "cceval-codex-l0-review-worker"
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


class CodexReviewError(RuntimeError):
    pass


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


def _dockerfile_hash() -> str:
    import hashlib

    dockerfile = _REPO_ROOT / "scripts" / "L0_proxy" / "codex" / "Dockerfile"
    return hashlib.sha256(dockerfile.read_bytes()).hexdigest()


def _ensure_container() -> None:
    check = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name={_CONTAINER_NAME}"],
        capture_output=True,
        text=True,
    )
    if check.stdout.strip():
        return

    dockerfile_hash = _dockerfile_hash()
    sentinel = _WORKSPACE_ROOT / _IMAGE_SENTINEL
    cached_hash = sentinel.read_text(encoding="utf-8").strip() if sentinel.is_file() else ""

    has_image = subprocess.run(
        ["docker", "images", "-q", _IMAGE_NAME],
        capture_output=True,
        text=True,
    ).stdout.strip()

    if not has_image or cached_hash != dockerfile_hash:
        dockerfile = _REPO_ROOT / "scripts" / "L0_proxy" / "codex" / "Dockerfile"
        print(f"Building Docker image {_IMAGE_NAME}...")
        ret = subprocess.run([
            "docker", "build", "-t", _IMAGE_NAME,
            "-f", str(dockerfile), str(dockerfile.parent),
        ])
        if ret.returncode != 0:
            raise CodexReviewError("Docker image build failed")
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text(dockerfile_hash, encoding="utf-8")

    _WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

    dotenv = _load_dotenv()
    env_args: list[str] = []

    openai_key = dotenv.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if openai_key:
        env_args += ["-e", f"OPENAI_API_KEY={openai_key}"]

    openai_base = os.environ.get("OPENAI_BASE_URL") or dotenv.get("OPENAI_BASE_URL")
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
        raise CodexReviewError(f"Container start failed: {ret.stderr}")

    codex_home = _WORKSPACE_ROOT / "codex_home"
    codex_home.mkdir(parents=True, exist_ok=True)
    (codex_home / "config.toml").write_text("", encoding="utf-8")

    print(f"Container started: {_CONTAINER_NAME}")
    print(f"Stop: docker stop {_CONTAINER_NAME} && docker rm {_CONTAINER_NAME}\n")


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


def _copy_repo_snapshot(repo_root: Path, dest_root: Path) -> None:
    from .repo_snapshot import IGNORED_DIR_NAMES

    if dest_root.exists():
        shutil.rmtree(dest_root)

    def _ignore(_dir: str, names: list[str]) -> set[str]:
        ignored = set()
        for name in names:
            if name in IGNORED_DIR_NAMES or name in {".DS_Store"}:
                ignored.add(name)
        return ignored

    shutil.copytree(repo_root, dest_root, ignore=_ignore)


def _workspace_for_run() -> tuple[Path, str]:
    _WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:12]
    workspace_dir = _WORKSPACE_ROOT / f"review_{run_id}"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return workspace_dir, run_id


def _write_artifacts(
    *,
    workspace_dir: Path,
    task_dir: Path,
    repo_root: Path,
    mode: str,
    prompt_text: str,
    analysis_prompt: str,
    extra_payload: dict,
    schema: dict,
) -> Path:
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (workspace_dir / "prompt.md").write_text(prompt_text, encoding="utf-8")
    (workspace_dir / "analysis_prompt.md").write_text(analysis_prompt, encoding="utf-8")
    (workspace_dir / "schema.json").write_text(
        json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (workspace_dir / "task.json").write_text(
        json.dumps({
            "task": f"{task_dir.parents[2].name}/{task_dir.parents[1].name}/{task_dir.name}",
            "mode": mode,
            **extra_payload,
        }, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _copy_repo_snapshot(repo_root, workspace_dir / "repo")
    return workspace_dir


def run_codex_review(
    *,
    task_dir: Path,
    repo_root: Path,
    mode: str,
    analysis_prompt: str,
    prompt_text: str,
    extra_payload: dict,
    schema: dict,
    model: str | None = None,
    timeout: int = 1200,
) -> dict:
    """Run Codex over a prepared workspace and return parsed JSON output."""
    _ensure_container()
    dotenv = _load_dotenv()
    openai_base = os.environ.get("OPENAI_BASE_URL") or dotenv.get("OPENAI_BASE_URL")
    codex_model = model or os.environ.get("CODEX_REVIEW_MODEL") or _DEFAULT_MODEL
    codex_config = _build_codex_config(codex_model, openai_base)
    codex_home = _WORKSPACE_ROOT / "codex_home"
    codex_home.mkdir(parents=True, exist_ok=True)
    (codex_home / "config.toml").write_text(codex_config, encoding="utf-8")

    workspace_dir, _run_id = _workspace_for_run()
    _write_artifacts(
        workspace_dir=workspace_dir,
        task_dir=task_dir,
        repo_root=repo_root,
        mode=mode,
        prompt_text=prompt_text,
        analysis_prompt=analysis_prompt,
        extra_payload=extra_payload,
        schema=schema,
    )

    final_message = workspace_dir / "final_message.json"
    cmd = [
        "docker", "exec", "-i",
        "-e", "CODEX_HOME=/workspaces/codex_home",
        _CONTAINER_NAME,
        "codex", "exec",
        "--cd", f"/workspaces/{workspace_dir.name}",
    ]
    if schema:
        cmd.extend([
            "--output-schema", f"/workspaces/{workspace_dir.name}/schema.json",
        ])
    cmd.extend([
        "--output-last-message", f"/workspaces/{workspace_dir.name}/final_message.json",
        "--model", codex_model,
        "--ephemeral",
        "--dangerously-bypass-approvals-and-sandbox",
        "--skip-git-repo-check",
        "--color", "never",
        "--json",
        "-",
    ])

    attempts = 2
    base_delay_s = 8.0
    last_error = ""

    prompt_path = workspace_dir / "analysis_prompt.md"
    prompt_text_to_send = prompt_path.read_text(encoding="utf-8")

    for attempt in range(1, attempts + 1):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=prompt_text_to_send,
            )
        except subprocess.TimeoutExpired as e:
            last_error = f"Codex timed out after {timeout}s"
            if attempt == attempts:
                raise CodexReviewError(last_error) from e
        else:
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            combined = f"{stdout}\n{stderr}".lower()

            if result.returncode == 0:
                if not final_message.exists():
                    raise CodexReviewError(
                        f"Codex did not write final_message.json.\nstdout: {stdout[:500]}\nstderr: {stderr[:500]}"
                    )
                try:
                    return json.loads(final_message.read_text(encoding="utf-8"))
                except json.JSONDecodeError as e:
                    raise CodexReviewError(
                        f"Invalid Codex JSON output.\nstdout: {stdout[:500]}\nstderr: {stderr[:500]}"
                    ) from e

            error_lines = stderr.splitlines()[-40:]
            for line in stdout.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "error":
                    error_lines.append(str(event.get("message", "")))
                if event.get("type") == "turn.failed":
                    error_lines.append(str(event.get("error", {}).get("message", "")))
            last_error = f"Codex failed (exit {result.returncode}):\n" + "\n".join(line for line in error_lines if line)
            retryable = any(pattern in combined for pattern in _RETRYABLE_PATTERNS)
            if not retryable or attempt == attempts:
                raise CodexReviewError(last_error)

        sleep_s = base_delay_s * (2 ** (attempt - 1)) + random.uniform(0, 2.0)
        print(f"Codex review retry {attempt}/{attempts} after {sleep_s:.1f}s: {last_error[:120]}")
        time.sleep(sleep_s)

    raise CodexReviewError(last_error or "Codex review failed")
